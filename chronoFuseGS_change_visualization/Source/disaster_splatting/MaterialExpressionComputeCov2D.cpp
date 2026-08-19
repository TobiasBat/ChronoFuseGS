// Fill out your copyright notice in the Description page of Project Settings.


#include "MaterialExpressionComputeCov2D.h"
#define LOCTEXT_NAMESPACE "MaterialExpressionMaterialXComputeCov2D"

UMaterialExpressionComputeCov2D::UMaterialExpressionComputeCov2D(const FObjectInitializer& ObjectInitializer) : 
	Super(ObjectInitializer)
{
	struct FConstructorStatics
	{
		FText YourCategory;
		FConstructorStatics(): YourCategory(LOCTEXT( "Gaussian Splatting", "Compute Cov 2D" ))
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
int32 UMaterialExpressionComputeCov2D::Compile(class FMaterialCompiler* Compiler, int32 OutputIndex)
{
	int32 MeanResultedID = Mean.Compile(Compiler);
	return MeanResultedID;
	// int32 InputBResultID = InputB.GetTracedInput().Expression ? InputB.Compile(Compiler) : Compiler->Constant(DefaultInputB);

	// int32 AddResultID = Compiler->Add(Arg1, Arg2)c;
    
	// if (!bNegateResult)
	// {
	// 	return AddResultID;
	// }
    
	// return Compiler->Mul(Compiler->Constant(-1.0f), AddResultID);
}

void UMaterialExpressionComputeCov2D::GetCaption(TArray<FString>& OutCaptions) const
{
	OutCaptions.Add(TEXT("MaterialX Compute Cov 2D"));
}

#endif

#undef LOCTEXT_NAMESPACE