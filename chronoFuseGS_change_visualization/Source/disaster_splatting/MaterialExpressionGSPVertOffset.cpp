// Fill out your copyright notice in the Description page of Project Settings.


#include "MaterialExpressionGSPVertOffset.h"

#include "MaterialCompiler.h"
#define LOCTEXT_NAMESPACE "MaterialExpressionMaterialXComputeCov2D"

UMaterialExpressionGSPVertOffset::UMaterialExpressionGSPVertOffset(const FObjectInitializer& ObjectInitializer) : 
	Super(ObjectInitializer)
{
	struct FConstructorStatics
	{
		FText YourCategory;
		FConstructorStatics(): YourCategory(LOCTEXT( "Gaussian Splatting", "GSP Vertex Offset" ))
		{
		}
	};
	static FConstructorStatics ConstructorStatics;

#if WITH_EDITORONLY_DATA
	MenuCategories.Add(ConstructorStatics.YourCategory);
#endif

	// DefaultMean = FVector3f(0.5f, 0.5f, 0.5f);
}

#if WITH_EDITOR
int32 UMaterialExpressionGSPVertOffset::Compile(class FMaterialCompiler* Compiler, int32 OutputIndex)
{
	// int32 MeanResultedID = Mean.Compile(Compiler);
	// return MeanResultedID;
	// int32 InputBResultID = InputB.GetTracedInput().Expression ? InputB.Compile(Compiler) : Compiler->Constant(DefaultInputB);

	// int32 AddResultID = Compiler->Add(Arg1, Arg2)c;
    
	// if (!bNegateResult)
	// {
	// 	return AddResultID;
	// }
    
	// return Compiler->Mul(Compiler->Constant(-1.0f), AddResultID);

	int32 TextCoordId = TextCoord.Compile(Compiler);
	int32 MeanScreenPosId = MeanScreenPos.Compile(Compiler);
	int32 SizeId = Size.Compile(Compiler);
	int32 Offset = Compiler->Mul(TextCoordId, SizeId);
	int32 OffsetedVertPos = Compiler->Add(MeanScreenPosId, Offset);
	
	return OffsetedVertPos;
}

void UMaterialExpressionGSPVertOffset::GetCaption(TArray<FString>& OutCaptions) const
{
	OutCaptions.Add(TEXT("GSP Vertex Offset"));
}

#endif

#undef LOCTEXT_NAMESPACE
