// Fill out your copyright notice in the Description page of Project Settings.

#pragma once

#include "CoreMinimal.h"
#include "Materials/MaterialExpression.h"
#include "MaterialExpressionGSPVertOffset.generated.h"

/**
 * 
 */
UCLASS()
class DISASTER_SPLATTING_API UMaterialExpressionGSPVertOffset : public UMaterialExpression
{
	GENERATED_BODY()
public:
	UMaterialExpressionGSPVertOffset(const FObjectInitializer& ObjectInitializer);

	
	UPROPERTY(meta = (RequiredInput = "true", ToolTip = "Vec2 Screen Coordinates"))
	FExpressionInput TextCoord;

	UPROPERTY(meta = (RequiredInput = "true", ToolTip = "Projected Mean of Splat"))
	FExpressionInput MeanScreenPos;

	UPROPERTY(meta = (RequiredInput = "true", ToolTip = "Debug Splat Size"))
	FExpressionInput Size;
	
#if WITH_EDITOR
	virtual int32 Compile(class FMaterialCompiler* Compiler, int32 OutputIndex) override;
	virtual FText GetCreationName() const override { return FText::FromString(TEXT("GSP Vertex Offset")); }
	virtual void GetCaption(TArray<FString>& OutCaptions) const override;
#endif
};
