// Fill out your copyright notice in the Description page of Project Settings.


#include "GaussianPositionCapturer.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Engine/Engine.h"
#include "Components/SceneCaptureComponent2D.h"
#include "DSP/BufferDiagnostics.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/GameViewportClient.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "MotionControllerComponent.h"
#include "XRMotionControllerBase.h"
#include "Camera/CameraTypes.h"
#include "Engine/TextureRenderTarget2D.h"
#include "SceneView.h" // For FSceneView and FMinimalViewInfo
#include "HAL/IConsoleManager.h"

// Sets default values
AGaussianPositionCapturer::AGaussianPositionCapturer()
{
 	// Set this actor to call Tick() every frame.  You can turn this off to improve performance if you don't need it.
	PrimaryActorTick.bCanEverTick = true;
	CaptureComponent = CreateDefaultSubobject<USceneCaptureComponent2D>(TEXT("CaptureComponent"));
	// RootComponent = CaptureComponent;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	CaptureComponent->SetupAttachment(RootComponent);
	
	RTWidth  = 1920;
	RTHeight = 1080;
	StaticRT = nullptr;
	RTInitialized = false;
	SplattingActor = nullptr;
	UseRightHand = false;
	ControllerOffsetRotation = FRotator(-45.0f, 0.0f, 0.0f);
	
	PosMultiplier = 6000.0; 
}

// Called when the game starts or when spawned
void AGaussianPositionCapturer::BeginPlay()
{
	Super::BeginPlay();
	// TryInitializeRT();
	InitRT();
	SplattingActor = Cast<ASplattingActor>(UGameplayStatics::GetActorOfClass(GetWorld(), ASplattingActor::StaticClass()));
	if (SplattingActor)
	{
		UE_LOG(LogTemp, Log, TEXT("Niagara Systems %i"), SplattingActor->NiagaraComponents.Num()); 
	}
}

// Called every frame
void AGaussianPositionCapturer::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	UpdateCapturer();
}

void AGaussianPositionCapturer::UpdateCapturer()
{
	if (!RTInitialized) return;

	if (SplattingActor->NiagaraPositionComponents.Num() > 0)
	{
		UNiagaraComponent* NiagaraPosComp = SplattingActor->NiagaraPositionComponents[0];
		CaptureComponent->PrimitiveRenderMode = ESceneCapturePrimitiveRenderMode::PRM_UseShowOnlyList;
		CaptureComponent->ShowOnlyComponent(NiagaraPosComp);
	} else
	{
		UE_LOG(LogTemp, Error, TEXT("No Niagara Pos Components"));
	}

	
	// Update Capture Component
	if (UseRightHand)
	{
	    // UE_LOG(LogTemp, Log, TEXT("Using Right Hand Controller")); 
		APawn* CurrentPawn = GetWorld()->GetFirstPlayerController()->GetPawn();
		if (!CurrentPawn)
		{
			UE_LOG(LogTemp, Error, TEXT("No Pawn"));
			return;
		}

		// Find all Motion Controller Components on the Pawn
		TArray<UMotionControllerComponent*> Controllers;
		CurrentPawn->GetComponents<UMotionControllerComponent>(Controllers);

		if (Controllers.Num() == 0)
		{
			UE_LOG(LogTemp, Error, TEXT("No Controllers"));
			return; 
		}
		
		for (UMotionControllerComponent* MC : Controllers)
		{
			// Check if this is the right hand
			if (MC->GetTrackingMotionSource() == FName("RightGrip"))
			{
				FVector Pos = MC->GetComponentLocation();
				FQuat AlignQuat = MC->GetComponentQuat() * FQuat(ControllerOffsetRotation);
    
				SetActorLocationAndRotation(Pos, AlignQuat);
				SplattingActor->SetParticleFacingPosition(Pos); 
				CaptureComponent->FOVAngle = FOVDeg;
				// float FOV = FOVDeg; // CaptureComponent->FOVAngle;
				float HalfFOV = FMath::DegreesToRadians(FOVDeg) * 0.5f;

				FVector ViewLocation = MC->GetComponentLocation();
				FRotator ViewRotation = AlignQuat.Rotator(); // MC->GetComponentRotation();
				float Width = StaticRT->SizeX;
				float Height = StaticRT->SizeY;

				// 2. Build the TranslatedWorldToView (Rotation Only)
				// This handles the swap: Unreal X-Forward -> View Z-Forward
				// FMatrix ViewRotationMatrix = FInverseRotationMatrix(ViewRotation) * FMatrix(
				// 	FVector(0, 0, 1), // View X (Right)
				// 	FVector(1, 0, 0), // View Y (Up)
				// 	FVector(0, 1, 0), // View Z (Forward)
				// 	FVector::ZeroVector
				// );
				FMatrix ViewRotationMatrix = FInverseRotationMatrix(ViewRotation) * FMatrix(
					FVector(0, 0, 1), // View X (Right)
					FVector(1, 0, 0), // View Y (Up)
					FVector(0, 1, 0), // View Z (Forward)
					FVector::ZeroVector
				);
				
				// 3. Build the Projection Matrix (Reversed-Z)
				// FMatrix ProjectionMatrix = FReversedZPerspectiveMatrix(
				// 	HalfFOV,
				// 	Width,
				// 	Height,
				// 	GNearClippingPlane
				// );
				// Not sure which I should take seams booth are working 
				FMatrix ProjectionMatrix = FPerspectiveMatrix(
					HalfFOV,
					Width,
					Height,
					GNearClippingPlane
				);
							
				// 4. Manual PreViewTranslation
				FVector PreViewTranslation = -ViewLocation;

				// 5. Construct FViewMatrices using the explicit constructor
				// Note: Depending on your exact UE5 sub-version, you may need to 
				// pass these into a constructor or simply calculate the combined matrices manually.
				FMatrix TranslatedWorldToView = ViewRotationMatrix;
				FMatrix ViewToClip = ProjectionMatrix;
				FMatrix TranslatedWorldToClip = ViewRotationMatrix * ProjectionMatrix;
				FMatrix ClipToTranslatedWorld = TranslatedWorldToClip.Inverse();

				// 6. Send to Niagara
				SplattingActor->SetDepthCameraMats(
					FVector2D(Width, Height),
					FVector4(PreViewTranslation, 0.0f),
					TranslatedWorldToView, 
					ViewToClip,
					ClipToTranslatedWorld
				);
				
				break; 
			}
		}
	} else
	{
		APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
		if (PC && PC->PlayerCameraManager)
		{
			// TODO Plugin in here an actor and take the position and rotation
			SetActorLocationAndRotation(
				PC->PlayerCameraManager->GetCameraLocation(),
				PC->PlayerCameraManager->GetCameraRotation()
			);
			CaptureComponent->FOVAngle = PC->PlayerCameraManager->GetFOVAngle();
		}
	}
}


void AGaussianPositionCapturer::TryInitializeRT()
{
	
	if (RTInitialized) return;
	if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport)
	{
		FIntPoint PhysSize = GEngine->GameViewport->Viewport->GetSizeXY();

		if (PhysSize.X > 0 && PhysSize.Y > 0)
		{
			RTWidth  = PhysSize.X;
			RTHeight = PhysSize.Y;
			UE_LOG(LogTemp, Log, TEXT("Capturer: physical size %dx%d"), RTWidth, RTWidth);

			InitRT();
			return;
		}
	}

	if (GEngine && GEngine->GameViewport && GEngine->GameViewport->Viewport)
	{
		ViewportResizedHandle = GEngine->GameViewport->Viewport->ViewportResizedEvent.AddUObject(
			this, &AGaussianPositionCapturer::OnViewportResized);
	}
}


void AGaussianPositionCapturer::InitRT()
{
	// if (RTWidth <= 0 || RTHeight <= 0)
	// {
	// 	RTWidth  = 1920;
	// 	RTHeight = 1080;
	// 	UE_LOG(LogTemp, Warning, TEXT("Capturer: invalid size, falling back to 1920x1080"));
	// }
// 
	// float ScreenPct = 100.f;
	// if (auto* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage")))
	// 	ScreenPct = CVar->GetFloat();
// 
	// RTWidth  = FMath::Max(1, FMath::RoundToInt(RTWidth  * ScreenPct / 100.f));
	// RTHeight = FMath::Max(1, FMath::RoundToInt(RTHeight * ScreenPct / 100.f));

	RTWidth = 300;
	RTHeight = 125;
	UE_LOG(LogTemp, Log, TEXT("Capturer RT Size %i %i"), RTWidth, RTHeight);

	if (!StaticRT)
	{
		StaticRT = NewObject<UTextureRenderTarget2D>(this);
		StaticRT->RenderTargetFormat = ETextureRenderTargetFormat::RTF_RGBA32f;
		StaticRT->InitCustomFormat(RTWidth, RTHeight, PF_FloatRGBA, false);
		StaticRT->TargetGamma = 1.0f;
		StaticRT->UpdateResource();
		
		CaptureComponent->TextureTarget = StaticRT;
		CaptureComponent->CaptureSource =  ESceneCaptureSource::SCS_SceneColorHDR;
		CaptureComponent->ShowFlags.SetPostProcessing(false);
		CaptureComponent->ShowFlags.SetTonemapper(false); // Explicitly kill the tonemapper
		CaptureComponent->ShowFlags.SetBloom(false);

		// 3. CRITICAL: Override Exposure to be 1.0 (Fixed)
		CaptureComponent->PostProcessSettings.bOverride_AutoExposureBias = true;
		CaptureComponent->PostProcessSettings.AutoExposureBias = 0.0f;
		CaptureComponent->PostProcessSettings.bOverride_AutoExposureMinBrightness = true;
		CaptureComponent->PostProcessSettings.AutoExposureMinBrightness = 1.0f;
		CaptureComponent->PostProcessSettings.bOverride_AutoExposureMaxBrightness = true;
		CaptureComponent->PostProcessSettings.AutoExposureMaxBrightness = 1.0f;
	}
	else
	{
		StaticRT->ResizeTarget(RTWidth, RTHeight);
		StaticRT->UpdateResource();
	}

	// SyncShowFlagsFromViewport();
	RTInitialized = true;
	
}


void AGaussianPositionCapturer::OnViewportResized(FViewport* Viewport, uint32)
{
	if (RTInitialized) return;

	FIntPoint PhysSize = Viewport->GetSizeXY();
	if (PhysSize.X <= 0 || PhysSize.Y <= 0) return;

	RTWidth  = PhysSize.X;
	RTHeight = PhysSize.Y;
	UE_LOG(LogTemp, Log, TEXT("Capturer: deferred init — physical size %dx%d"), RTWidth, RTHeight);

	InitRT();

	// Unbind — we only need this once
	Viewport->ViewportResizedEvent.Remove(ViewportResizedHandle);
	ViewportResizedHandle.Reset();
}


FVector AGaussianPositionCapturer::ReadPosition(float U, float V)
{
	auto Result = FVector::Zero();
	if (StaticRT == nullptr)
	{
		UE_LOG(LogTemp, Error, TEXT("Position RT pointer is null"));
		return Result;
	}

	if (U < 0 || U > 1 || V < 0 || V > 1)
	{
		UE_LOG(LogTemp, Error, TEXT("UV are not [0,1] %f %f"), U, V);
		return Result; 
	}

	// 1. Get Resource
	FTextureRenderTargetResource* RTResource = StaticRT->GameThread_GetRenderTargetResource();
	if (!RTResource) return Result;

	// 2. Clamp coordinates to ensure we are inside the texture bounds
	int32 X = static_cast<int32>(U * StaticRT->SizeX);
	int32 Y = static_cast<int32>(V * StaticRT->SizeY);

	TArray<FLinearColor> OutSamples;
	FIntRect SampleRect(X, Y, X + 1, Y + 1);

	// RTResource->ReadLinearColorPixels(OutSamples, FReadSurfaceDataFlags(), SampleRect);
	RTResource->ReadLinearColorPixels(OutSamples, FReadSurfaceDataFlags(RCM_MinMax), SampleRect);
	for (auto S : OutSamples)
	{
		Result.X += S.R / OutSamples.Num();
		Result.Y += S.G / OutSamples.Num();
		Result.Z += S.B / OutSamples.Num();
	}

	Result.X -= 0.5f;
	Result.Y -= 0.5f;
	Result.Z -= 0.5f;
	Result *= PosMultiplier;
	
	return Result;
}


FMatrix AGaussianPositionCapturer::GetCaptureProjectionMatrix()
{
	if (!CaptureComponent || !CaptureComponent->TextureTarget) return FMatrix::Identity;

	float const TargetWidth = CaptureComponent->TextureTarget->SizeX;
	float const TargetHeight = CaptureComponent->TextureTarget->SizeY;

	float const HalfFOV = FMath::DegreesToRadians(CaptureComponent->FOVAngle) * 0.5f;
	
	return FPerspectiveMatrix(HalfFOV, TargetWidth, TargetHeight, GNearClippingPlane);
}